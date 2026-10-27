#include "BoundaryWeightedPool.hpp"
#include "StarWeightedPool.hpp"
struct FriendRange {
 friend struct Star::WeightedPool<int>;
 friend struct Star::BoundaryWeightedPool<int>;
 FriendRange()=default;
private:
 Star::pair<double,int> values[1]{{1,10}};
 auto begin(){return values;}
 auto end(){return values+1;}
};
void friend_access_probe(){
#if WP_FRIEND_ORIGINAL
 Star::WeightedPool<int> pool(FriendRange{});
#else
 Star::BoundaryWeightedPool<int> pool(FriendRange{});
#endif
 (void)pool;
}
